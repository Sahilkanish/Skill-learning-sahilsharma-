def my_function():
    print("this is my function")
my_function()

def my_function(Fname):
    print(Fname +"sharma")
my_function("sahil-1")
my_function("sahil-2")
my_function("sahil-3")

def my_function(fname,lname):
    print(fname+""+lname)
my_function("sahil","sharma")

def my_function(*student):
    print("Topper of class is"+ student[0])
my_function("sahil","aman","rohit","mohit")

def my_function(child3,child2,child1):
    print("the youngest child is"+child2)

my_function(child1="pankaj",
            child2="mohit",
            child3="sahil")

def my_function(**kid):
    print("the lastname is" + kid ["lname"])
my_function(fname="sahil",
            lname="sharma")


list=[1,2,3,4,5,6,7,43,335,67,8]
length=len(list)
print(f"this is the length of the list:{length}")
final_index=(length-1)
print(f"this is the final index of the list:{final_index}")

numbers=[23,5,42,12,37,1,30,16,48,55,8,19,51,26,34,44,0,29,53,39,
         10,31,17,57,3,25,46,22,14,49,6,41,58,20,36,9,52,7,28,45,
         15,43,2,24,38,11,33,50,4,59,13,35,18,21,47,27,32,40,54,56]
length=len(numbers)
print(f"this is the length of the list:{length}")
final_index=(length-1)
print(f"this is the final index of the list:{final_index}")
